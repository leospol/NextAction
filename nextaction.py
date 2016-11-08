#!/usr/bin/env python

import logging
import argparse

# noinspection PyPackageRequirements
from todoist.api import TodoistAPI

import time
import sys
from datetime import datetime


class Item(object):
    def __init__(self, items):
        item = items.pop(0)
        self.id = item["id"]
        self.content = item["content"]
        self.labels = item["labels"]
        self.due_date_utc = item["due_date_utc"]
        self.checked = item["checked"]
        self.children = []
        self.active = False

        while items and item["indent"] < items[0]["indent"]:
            self.children.append(Item(items))

    def __str__(self):
        return "<Item id={} content={}" \
               " checked={} labels={}>".format(self.id,
                                               self.content,
                                               self.checked,
                                               self.labels)


class NextAction(object):
    def __init__(self):
        self.args = None
        self.api = None
        self.next_label_id = None
        self.waitfor_label_id = None
        self.active_label_id = None

    def main(self):
        self.setup()
        self.loop()

    def check_label(self, label):
        # Check if the label exists
        labels = self.api.labels.all(lambda x: x['name'] == label)
        if len(labels) > 0:
            label_id = labels[0]['id']
            logging.debug('Label %s found as label id %d', label, label_id)
            return label_id
        else:
            logging.error(
                "Label %s doesn't exist.", label)
            sys.exit(1)

    def setup(self):
        self.parse_args()

        # Run the initial sync
        logging.debug('Connecting to the Todoist API')
        self.api = TodoistAPI(token=self.args.api_key)
        logging.debug('Syncing the current state from the API')
        self.api.sync()
        self.next_label_id = self.check_label(self.args.label)
        self.active_label_id = self.check_label(self.args.active)
        self.waitfor_label_id = self.check_label(self.args.waitfor)

    def loop(self):
        """
        Main loop
        """
        while True:
            try:
                self.api.sync()
            except Exception as exc:
                logging.exception('Error trying to sync with Todoist API: %s',
                                  exc)
            else:
                self.process(self.api.projects.all())

                logging.debug(
                    '%d changes queued for sync... committing if needed',
                    len(self.api.queue))
                if len(self.api.queue):
                    self.api.commit()

            if self.args.onetime:
                break
            logging.debug('Sleeping for %d seconds', self.args.delay)
            time.sleep(self.args.delay)

    def process(self, projects, parent_indent=0, parent_type=None):
        """
        Process all projects
        """
        current_type = parent_type
        while projects and parent_indent < projects[0]["indent"]:
            # dig deeper
            if projects[0]["indent"] > parent_indent + 1:
                self.process(projects, parent_indent + 1, current_type)
                continue

            project = projects.pop(0)
            current_type = self.get_project_type(project, parent_type)
            if not current_type:
                # project not marked - not touching
                continue

            logging.debug('Project %s being processed as %s',
                          project['name'], current_type)

            def item_filter(x):
                return x['project_id'] == project['id']

            all_items = self.api.items.all(item_filter)
            items = sorted(all_items, key=lambda x: x['item_order'])
            item_objs = []
            while items:
                item_objs.append(Item(items))
            self.process_items(item_objs, current_type)
            self.activate(item_objs)

    def process_items(self, items, parent_type, not_in_first=False):
        """
        Process all tasks in project
        """
        # get the first item for serial
        first = None
        if parent_type == "serial":
            not_checked = [item for item in items if not item.checked]
            if not_checked and not self.is_waitfor(not_checked[0]):
                first = not_checked[0]

        # process items
        parent_active = False
        for item in items:
            current_type = self.get_item_type(item)

            if current_type:
                logging.debug('Identified %s as %s type', item.content,
                              current_type)
            else:
                current_type = parent_type

            if item.children:
                active = self.process_items(item.children, current_type,
                                            not_in_first or
                                            first and item != first)
            else:
                active = False

            if self.check_future(item):
                continue

            active |= self.process_item(item, parent_type, first, not_in_first)
            item.active = active
            parent_active |= active
        return parent_active

    def process_item(self, item, type, first=None, not_in_first=False):
        """
        Process single item
        """
        # untag if checked
        if item.checked or not_in_first:
            return self.remove_label(item, self.next_label_id)
        # don't tag if parent with unchecked child
        elif [child for child in item.children if not child.checked]:
            return self.remove_label(item, self.next_label_id)
        # tag all parallel but not waitfors
        elif type == "parallel" and not self.is_waitfor(item):
            return self.add_label(item, self.next_label_id)
        # tag the first serial
        elif type == "serial" and item == first:
            return self.add_label(item, self.next_label_id)
        # untag otherwise
        else:
            return self.remove_label(item, self.next_label_id)

    def activate(self, items):
        """
        Mark indent 1 items as active if supposed to be
        """
        for item in items:
            if item.active:
                self.add_label(item, self.active_label_id)
            else:
                self.remove_label(item, self.active_label_id)

    def check_future(self, item):
        """
        If its too far in the future, remove the next_action tag and skip
        """
        if self.args.hide_future > 0 and item.due_date_utc:
            due_date = datetime.strptime(item.due_date_utc,
                                         '%a %d %b %Y %H:%M:%S +0000')
            future_diff = (due_date - datetime.utcnow()).total_seconds()
            if future_diff >= (self.args.hide_future * 86400):
                self.remove_label(item, self.next_label_id)
                return True

    def get_project_type(self, project_object, parent_type):
        """
        Identifies how a project should be handled
        """
        name = project_object['name'].strip()
        if name == 'Inbox':
            return self.args.inbox
        elif name[-1] == self.args.parallel_suffix:
            return 'parallel'
        elif name[-1] == self.args.serial_suffix:
            return 'serial'
        elif parent_type:
            return parent_type

    def get_item_type(self, item):
        """
        Identifies how a item with sub items should be handled
        """
        name = item.content.strip()
        if name[-1] == self.args.parallel_suffix:
            return 'parallel'
        elif name[-1] == self.args.serial_suffix:
            return 'serial'

    def add_label(self, item, label):
        if label not in item.labels:
            labels = item.labels
            logging.debug('Updating %s with label %s', item.content, label)
            labels.append(label)
            self.api.items.update(item.id, labels=labels)
        return True

    def remove_label(self, item, label):
        if label in item.labels:
            labels = item.labels
            logging.debug('Updating %s without label %s', item.content, label)
            labels.remove(label)
            self.api.items.update(item.id, labels=labels)
        return False

    def is_waitfor(self, item):
        return self.waitfor_label_id in item.labels

    @staticmethod
    def get_subitems(items, parent_item=None):
        """
        Search a flat item list for child items
        """
        result_items = []
        found = False
        if parent_item:
            required_indent = parent_item['indent'] + 1
        else:
            required_indent = 1
        for item in items:
            if parent_item:
                if not found and item['id'] != parent_item['id']:
                    continue
                else:
                    found = True
                if item['indent'] == parent_item['indent'] and item['id'] != \
                        parent_item['id']:
                    return result_items
                elif item['indent'] == required_indent and found:
                    result_items.append(item)
            elif item['indent'] == required_indent:
                result_items.append(item)
        return result_items

    def parse_args(self):
        """
        Parse command-line arguments
        """
        parser = argparse.ArgumentParser()
        parser.add_argument('-a', '--api_key', help='Todoist API Key')
        parser.add_argument('-l', '--label',
                            help='The next action label to use',
                            default='next_action')
        parser.add_argument('-c', '--active',
                            help='The active level1 parent label',
                            default='active')
        parser.add_argument('-w', '--waitfor',
                            help='The waitfor label',
                            default='waitfor')
        parser.add_argument('-d', '--delay',
                            help='Specify the delay in seconds between syncs',
                            default=5, type=int)
        parser.add_argument('--debug', help='Enable debugging',
                            action='store_true')
        parser.add_argument('--inbox',
                            help='The method the Inbox project should '
                                 'be processed',
                            default='parallel', choices=['parallel', 'serial'])
        parser.add_argument('--parallel_suffix', default='.')
        parser.add_argument('--serial_suffix', default='_')
        parser.add_argument('--hide_future',
                            help='Hide future dated next actions until the '
                                 'specified number of days',
                            default=7, type=int)
        parser.add_argument('--onetime', help='Update Todoist once and exit',
                            action='store_true')
        self.args = parser.parse_args()

        # Set debug
        if self.args.debug:
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO
        logging.basicConfig(level=log_level)

        # Check we have a API key
        if not self.args.api_key:
            logging.error('No API key set, exiting...')
            sys.exit(1)


if __name__ == '__main__':
    NextAction().main()

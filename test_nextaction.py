#!/usr/bin/env python
import unittest
import datetime
from mock import Mock, call
from nextaction import NextAction, Item


class TestProjects(unittest.TestCase):
    def setUp(self):
        self.na = NextAction()
        self.na.api = Mock()
        self.na.args = Mock()
        self.na.api.items.all.return_value = []
        self.na.args.parallel_suffix = ":"
        self.na.args.serial_suffix = "."

    def test_ignore_not_marked_empty(self):
        """
        Not marked projects are ignored
        """
        self.na.api.projects.all.return_value = []
        self.na.process(self.na.api.projects.all())

    def test_ignore_not_marked(self):
        """
        Not marked projects are ignored
        """
        project1 = {"name": "project1.", "indent": 1}
        project2 = {"name": "project2", "indent": 1}
        self.na.process_items = Mock()
        self.na.api.projects.all.return_value = [project1, project2]
        self.na.process(self.na.api.projects.all())
        self.na.process_items.assert_called_once_with([], "serial")

    def test_inherit_type(self):
        """
        Inherit project type from parent
        """
        project1 = {"name": "project1.", "indent": 1}
        project2 = {"name": "project2", "indent": 2}
        project3 = {"name": "project3:", "indent": 2}
        project4 = {"name": "project4:", "indent": 1}
        self.na.process_items = Mock()
        self.na.api.projects.all.return_value = [project1, project2, project3,
                                                 project4]
        self.na.process(self.na.api.projects.all())
        calls = [call([], "serial"), call([], "serial"),
                 call([], "parallel"), call([], "parallel")]
        self.assertListEqual(self.na.process_items.call_args_list, calls)


class TestItems(unittest.TestCase):
    def setUp(self):
        self.na = NextAction()
        self.na.next_label_id = 1234
        self.na.waitfor_label_id = 2345
        self.na.active_label_id = 3456
        self.na.api = Mock()
        self.na.args = Mock()
        self.na.args.parallel_suffix = ":"
        self.na.args.serial_suffix = "."

    @staticmethod
    def make_obj(items):
        item_objs = []
        while items:
            item_objs.append(Item(items))
        return item_objs

    def test_inherit_from_project(self):
        """
        Inherit item type from project
        """

        # add label
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [987], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1])
        self.na.process_items(items, "serial")
        self.na.api.items.update.assert_called_once_with(1, labels=[987, 1234])

        # remove label
        self.na.api.items.update.reset_mock()
        item1["labels"] = [1234]
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [987, 1234], "checked": False, "due_date_utc": None}
        items = self.make_obj([item1, item2])
        self.na.process_items(items, "serial")
        self.na.api.items.update.assert_called_once_with(2, labels=[987])

    def test_inherit_from_parent(self):
        """
        Inherit item type from parent
        """

        # add label
        item1 = {"item_order": 1, "content": "item1:", "indent": 1, "id": 1,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 2, "id": 2,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [987], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(2, labels=[987, 1234]), call(3, labels=[987, 1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

        # remove label
        self.na.api.items.update.reset_mock()
        item1 = {"item_order": 1, "content": "item1.", "indent": 1, "id": 1,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 2, "id": 2,
                 "labels": [987, 1234], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [987, 1234], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(3, labels=[987])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_overwrite_type(self):
        """
        Item type can be overwritten
        """

        # add label
        item1 = {"item_order": 1, "content": "item1:", "indent": 1, "id": 1,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 2, "id": 2,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [987], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(2, labels=[987, 1234]), call(3, labels=[987, 1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

        # remove label
        self.na.api.items.update.reset_mock()
        item1 = {"item_order": 1, "content": "item1.", "indent": 1, "id": 1,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 2, "id": 2,
                 "labels": [987, 1234], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [987, 1234], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(3, labels=[987])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_items_are_labeled_parallel(self):
        """
        Label parallel items
        """
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 1, "id": 3,
                 "labels": [], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "parallel")
        calls = [call(1, labels=[987, 1234]), call(2, labels=[1234]),
                 call(3, labels=[1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_items_are_labeled_serial(self):
        """
        Label serial items
        """
        # add label
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 1, "id": 3,
                 "labels": [], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(1, labels=[987, 1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

        # remove label
        self.na.api.items.update.reset_mock()
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [987], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [1234], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 1, "id": 3,
                 "labels": [1234], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(1, labels=[987, 1234]), call(2, labels=[]),
                 call(3, labels=[])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

        # add label to the first item
        self.na.api.items.update.reset_mock()
        project1 = {"name": "project1.", "indent": 1, "id": 1}
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [987], "checked": True, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 1, "id": 3,
                 "labels": [], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(2, labels=[1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_overwrite_item_type(self):
        """
        Item type can be overwritten
        """
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2.", "indent": 2, "id": 2,
                 "labels": [], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 3, "id": 3,
                 "labels": [], "checked": False, "due_date_utc": None}
        item4 = {"item_order": 4, "content": "item4", "indent": 3, "id": 4,
                 "labels": [], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3, item4])
        self.na.process_items(items, "serial")
        calls = [call(3, labels=[1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_waitfor_serial(self):
        """
        Serial items are blocked by waitfor
        """
        item1 = {"item_order": 1, "content": "item1.", "indent": 1, "id": 1,
                 "labels": [], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 2, "id": 2,
                 "labels": [1234, 2345], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(2, labels=[2345])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_waitfor_parallel(self):
        """
        Parallel item is unlabeled by waitfor
        """
        item1 = {"item_order": 1, "content": "item1:", "indent": 1, "id": 1,
                 "labels": [], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 2, "id": 2,
                 "labels": [1234, 2345], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [1234], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "parallel")
        calls = [call(2, labels=[2345])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_future(self):
        self.na.args.hide_future = 5
        fmt = "%a %d %b %Y %H:%M:%S +0000"
        now = datetime.datetime.now()
        now6 = now + datetime.timedelta(days=6)
        now4 = now + datetime.timedelta(days=4)
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [1234], "due_date_utc": now6.strftime(fmt),
                 "checked": False}
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [], "due_date_utc": now6.strftime(fmt),
                 "checked": False}
        item3 = {"item_order": 3, "content": "item3", "indent": 1, "id": 3,
                 "labels": [], "due_date_utc": now4.strftime(fmt),
                 "checked": False}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "parallel")
        calls = [call(1, labels=[]), call(3, labels=[1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_checked_serial(self):
        """
        Serial items are checked, parent should be tagged
        """
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 2, "id": 2,
                 "labels": [1234], "checked": True, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [], "checked": True, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(2, labels=[]), call(1, labels=[1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_checked_parallel(self):
        """
        Serial items are checked, parent should be tagged
        """
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 2, "id": 2,
                 "labels": [1234], "checked": True, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [], "checked": True, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "parallel")
        calls = [call(2, labels=[]), call(1, labels=[1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_children_first_serial(self):
        """
        Children can be tagged only for the first serial parent
        """
        # add label
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(1, labels=[1234])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

        # remove label
        self.na.api.items.update.reset_mock()
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [1234], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [1234], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3])
        self.na.process_items(items, "serial")
        calls = [call(3, labels=[])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)

    def test_active_indent_1(self):
        """
        Items indent 1 should be active when at least one child is tagged
        """
        item1 = {"item_order": 1, "content": "item1", "indent": 1, "id": 1,
                 "labels": [1234], "checked": False, "due_date_utc": None}
        item2 = {"item_order": 2, "content": "item2", "indent": 1, "id": 2,
                 "labels": [], "checked": False, "due_date_utc": None}
        item3 = {"item_order": 3, "content": "item3", "indent": 2, "id": 3,
                 "labels": [1234], "checked": False, "due_date_utc": None}
        item4 = {"item_order": 2, "content": "item4", "indent": 1, "id": 4,
                 "labels": [], "checked": False, "due_date_utc": None}
        item5 = {"item_order": 3, "content": "item5", "indent": 2, "id": 5,
                 "labels": [2345], "checked": False, "due_date_utc": None}

        items = self.make_obj([item1, item2, item3, item4, item5])
        self.na.process_items(items, "parallel")
        self.na.activate(items)
        calls = [call(1, labels=[1234, 3456]), call(2, labels=[3456])]
        self.assertListEqual(self.na.api.items.update.call_args_list, calls)


if __name__ == '__main__':
    unittest.main()

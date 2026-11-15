"""System messages follow language preferences without translating user content."""
import json
import unittest
from backend.notification_copy import inbox_template,message,packs
from backend.tests import test_task_reminders as task_fixtures


class NotificationLocaleTests(unittest.TestCase):
    setUp=task_fixtures.TaskReminderTests.setUp
    task=task_fixtures.TaskReminderTests.task
    schedule=task_fixtures.TaskReminderTests.schedule
    save=task_fixtures.TaskReminderTests.save
    jobs=task_fixtures.TaskReminderTests.jobs

    def test_all_sixteen_templates_and_encrypted_subscription_language_refresh(self):
        for locale in packs():
            for key in ('system_task_reminder','system_calendar_reminder','system_test_notification','system_test_notification_queued','system_budget_threshold'):
                self.assertTrue(message(key,locale))
            self.assertIn('{threshold}',message('system_budget_threshold',locale))
        self.push.subscribe(self.actor,{'subscription':self.subscription,'lead_minutes':15,'priority':'high','timezone':'UTC','locale':'de'})
        self.save(self.task())
        self.push.scan()
        job=self.jobs()[0]
        payload=json.loads(self.backend.cipher.decrypt(bytes(job['payload'])))
        self.assertEqual(payload['body'],'Aufgabenerinnerung')
        self.push.subscribe(self.actor,{'subscription':self.subscription,'lead_minutes':15,'priority':'high','timezone':'UTC','locale':'uk'})
        self.assertEqual(self.jobs()[0]['state'],'queued')
        with self.backend.connect() as db:
            raw=db.execute('SELECT secret FROM web_push_subscriptions').fetchone()['secret']
        self.assertEqual(json.loads(self.backend.cipher.decrypt(bytes(raw)))['locale'],'uk')
        with self.assertRaises(Exception):
            self.push.subscribe(self.actor,{'subscription':self.subscription,'timezone':'UTC','locale':'unknown'})

    def test_only_system_producers_receive_known_message_templates(self):
        announcement={'kind':'announcement','title':'PRIVATE TITLE','body':'Напоминание о задаче','link':'/app'}
        self.assertEqual(inbox_template(announcement),{})
        note={'kind':'reminder','body':'Напоминание о задаче','link':'/app?notification=task&workspace=synthetic&task=synthetic'}
        self.assertEqual(inbox_template(note)['message_key'],'system_task_reminder')
        budget={'kind':'budget','body':'Достигнут порог расходов бюджета: 80%.','link':'/app?tab=money'}
        self.assertEqual(inbox_template(budget)['message_args'],{'threshold':80})
        self.assertEqual(inbox_template({**budget,'body':'PRIVATE USER BODY'}),{})


if __name__=='__main__':unittest.main()

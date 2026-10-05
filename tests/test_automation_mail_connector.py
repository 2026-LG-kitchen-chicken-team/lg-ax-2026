import base64
import unittest
from email.message import EmailMessage

from services.automation.mail_connector import CodexGmailTransport, ConnectorError


class ConnectorTransportTests(unittest.TestCase):
    def transport(self, responses):
        class Stub(CodexGmailTransport):
            def __init__(self):
                self.calls = []
            def _call(self, tool, arguments):
                self.calls.append((tool, arguments))
                return responses[tool]
        return Stub()

    def test_only_known_routes_and_no_unknown_send_headers(self):
        transport = self.transport({})
        with self.assertRaises(ConnectorError):
            transport.request('DELETE', 'messages/0123456789abcdef')
        with self.assertRaises(ConnectorError):
            transport.request('POST', 'messages/send', {'raw':'', 'destination':'elsewhere'})
        self.assertEqual(transport.calls, [])

    def test_profile_and_search_use_connector_output_without_auth_copy(self):
        transport = self.transport({'gmail.get_profile':{'email':'pm@example.test'},
            'gmail.search_email_ids':{'ids':['1234567890abcdef'], 'next_page_token':'later'}})
        self.assertEqual(transport.request('GET','profile'), {'emailAddress':'pm@example.test'})
        result = transport.request('GET','messages',params={'q':'subject:fixed-action','maxResults':2})
        self.assertEqual(result['messages'], [{'id':'1234567890abcdef'}])
        self.assertEqual(result['nextPageToken'], 'later')
        self.assertFalse(transport.supports_custom_message_id)

    def test_plain_send_preserves_text_and_subject_and_uses_authenticated_from(self):
        transport = self.transport({'gmail.send_email':{'id':'1234567890abcdef','thread_id':'abcdef1234567890'}})
        message = EmailMessage()
        message['From']='pm@example.test'
        message['To']='member@example.test'
        message['Subject']='[LG AX] fixed-action'
        message['Message-ID']='<opaque-delivery@example.test>'
        message.set_content('고정 작업\n두 번째 줄\n')
        result = transport.request('POST','messages/send',{'raw':base64.urlsafe_b64encode(message.as_bytes()).decode()})
        self.assertEqual(result['threadId'],'abcdef1234567890')
        tool, payload = transport.calls[0]
        self.assertEqual(tool,'gmail.send_email')
        self.assertEqual(payload['from_address'],'pm@example.test')
        self.assertEqual(payload['payload']['body']['content'],'고정 작업\n두 번째 줄\n')
        self.assertNotIn('Message-ID',payload)

    def test_cc_multipart_or_duplicate_recipients_cannot_expand_notification(self):
        transport = self.transport({})
        for option in ['cc','multipart','duplicate']:
            message = EmailMessage()
            message['From']='pm@example.test'; message['To']='member@example.test'; message['Subject']='fixed'
            message.set_content('one')
            if option=='cc': message['Cc']='unexpected@example.test'
            if option=='multipart': message.add_alternative('<p>one</p>',subtype='html')
            if option=='duplicate': message._headers.append(('To','unexpected@example.test'))
            with self.assertRaises(ConnectorError):
                transport.request('POST','messages/send',{'raw':base64.urlsafe_b64encode(message.as_bytes()).decode()})
        self.assertEqual(transport.calls,[])


if __name__=='__main__':
    unittest.main()

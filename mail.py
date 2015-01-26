#!/bin/env python2
import smtpd
import asyncore
import email
from email.header import decode_header
from jinja2 import Environment, FileSystemLoader
import sys
import signal
import json
import os
import base64

class CustomSMTPServer(smtpd.SMTPServer):
    templateEnv   = Environment(loader=FileSystemLoader('.'))
    TEMPLATE_FILE = "mail.jinja"
    JSON_FILE     = "mail.json"
    OUTPUT_FILE   = "../public_html/mail.html"
    template      = templateEnv.get_template(TEMPLATE_FILE)
    maxmails      = 20
    mails         = []

    def signal_handler(self, signal, frame):
        print('Bye!')
        sys.exit(0)

    def __init__(self, localaddr, remoteaddr):
        """init smtp-server and read saved messages from JSON file"""
        smtpd.SMTPServer.__init__(self, localaddr, remoteaddr)
        if os.path.isfile(self.JSON_FILE):
            with open(self.JSON_FILE, 'r') as f:
                self.mails = json.load(f)
        self.render()

    def getheader(self, header_text, default="ascii"):
        """Decode the specified header"""
        headers = decode_header(header_text)
        header_sections = [unicode(text, charset)
                           for text, charset in headers]
        return u"".join(header_sections)

    def render(self):
        """ save mails as HTML and JSON file"""
        templateVars = {"mails": enumerate(self.mails)}
        outputText = self.template.render(templateVars)
        with open(self.OUTPUT_FILE, 'w') as f:
            f.write(outputText.encode("utf-8"))
        with open(self.JSON_FILE, 'w') as outfile:
            json.dump(self.mails, outfile, encoding="utf-8")

    def find_payload(self, msg, mimetype):
        """Find first payload of a specific type
           works with nested multipart messages"""
        if msg.get_content_type() == mimetype:
            return (msg.get_payload(decode=True), msg.get_content_charset())
        if msg.is_multipart():
            for payload in msg.get_payload():
                ret = self.find_payload(payload, mimetype)
                if ret != ("", None): return ret
        return ("", None)

    def process_message(self, peer, mailfrom, rcpttos, data):
        """Server received a new message, save it to the list and regenerate
           the HTML and JSON file"""
        msg = email.message_from_string(data)
        maildict = {}

        maildict["plaintext"], maildict["plaintext-cs"] = self.find_payload(msg, "text/plain")
        maildict["html"], maildict["html-cs"]           = self.find_payload(msg, "text/html")
        maildict["plaintext"] = base64.b64encode(maildict["plaintext"])
        maildict["html"]      = base64.b64encode(maildict["html"])
        maildict["from"]      = mailfrom
        maildict["to"]        = ", ".join(rcpttos)
        maildict["subject"]   = self.getheader(msg.get("Subject", ""))
        maildict["date"]      = msg.get("Date", "")

        self.mails.insert(0, maildict)
        while len(self.mails) > self.maxmails:
            self.mails.pop()
        self.render()
        return

server = CustomSMTPServer(('109.230.236.97', 25), None)
signal.signal(signal.SIGINT, server.signal_handler)
asyncore.loop()

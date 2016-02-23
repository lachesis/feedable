#!/usr/bin/python3
from __future__ import (
    absolute_import,
    division,
    print_function,
)

import argparse
import datetime
import json
import logging
import re
import subprocess
import threading

from email.mime.text import MIMEText
from six.moves.SimpleHTTPServer import BaseHTTPRequestHandler
from six.moves import socketserver

EPOCH = datetime.datetime(1970, 1, 1, 0, 0, 0)

logger = logging.getLogger(__name__)

clients = {}
lock = threading.Lock()

def dt2unix(dt):
    if dt is None:
        return dt
    return int((dt - EPOCH).total_seconds())

def send_email(email, obj, online):
    logger.info("Emailing %r about host %r in state %r", email, obj['client'],
                'online' if online else 'offline')

    if online:
        body = 'Host %r is back online as of %r.' % (obj['client'], obj['last_ping'])
        subject = '[%r] Back Online'
    else:
        body = 'Host %r is down! It has not been seen since %r.' % (obj['client'], obj['last_ping'])
        subject = '[%r] DOWN!'

    msg = MIMEText(body)
    msg["To"] = email
    msg["Subject"] = subject

    p = subprocess.Popen(["sendmail", "-t", "-oi"], stdin=subprocess.PIPE)
    p.communicate(msg.as_string())

def wake_up(email, client):
    should_send = False
    with lock:
        obj = clients[(email, client)]

        if obj['last_ping'] + datetime.timedelta(0, obj['interval']) < datetime.datetime.utcnow():
            logger.info("client %r missed check-in!", (email, client))
            obj['online'] = False
            should_send = True

    if should_send:
        send_email(email, obj, False)
    else:
        logger.debug("spurious wakeup!")

class Handler(BaseHTTPRequestHandler):
    def _report_stats(self):
        with lock:
            out = [{
                'email': client.get('email'),
                'client': client.get('client'),
                'interval': client.get('interval'),
                'last_ping': dt2unix(client.get('last_ping')),
                'online': client.get('online'),
            } for client in clients.values()]

        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({'data': out}, indent=4).encode('utf-8'))

    def do_GET(self):
        # Figure out if this is a request for stats - if so, call that method
        if self.path == '/feed/stats':
            return self._report_stats()

        # Now check if this is a normal ping request
        try:
            _, base, email, client, interval = self.path.split('/')
            assert base == 'feed'
            interval = int(interval)
            assert interval >= 0
        except Exception:
            self.send_error(404, 'Not Found')
            return

        with lock:
            key = (email, client)

            if key not in clients:
                clients[key] = {
                    'email': email,
                    'client': client,
                    'online': True,
                }

                logger.info("registering new client %r with interval %r", key, interval)
            else:
                # Cancel our pending wakeup (if there is one)
                clients[key]['timer'].cancel()
                logger.debug("handling ping for client %r with interval %r", key, interval)

            clients[key]['last_ping'] = datetime.datetime.utcnow()
            clients[key]['interval'] = interval

            # If we were offline, send an email saying we're back (in another thread)
            if clients[key]['online'] is False:
                timer = threading.Timer(0, lambda: send_email(email, clients[key], True))
                timer.start()

            clients[key]['online'] = True

            # Schedule our next wakeup
            timer = threading.Timer(interval + 1, lambda: wake_up(email, client))
            timer.daemon = True
            clients[key]['timer'] = timer
            timer.start()

        self.send_response(200)
        self.end_headers()

def main():
    parser = argparse.ArgumentParser(description='Stupid simple watchdog')
    parser.add_argument('--port', '-p', dest='port', type=int, required=True, help='port to listen on')
    parser.add_argument('--debug', '-d', dest='debug', action='store_true', help='debug logging?')

    args = parser.parse_args()

    logging.basicConfig(level=(logging.DEBUG if args.debug else logging.INFO))

    httpd = socketserver.TCPServer(("", args.port), Handler)

    logger.info("serving at port %r", args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("goodbye")
    finally:
        httpd.shutdown()
        httpd.server_close()

if __name__ == '__main__':
    main()

Stupid simple watchdog. It'll email you when your computer is down.

Server setup
------------
Install:
```
pip install feedable
```

Run:
```
feedable -p 14567
```
I like to run this under `supervisor`, but you can also use -d if you're
adventurous. You can also put this behind nginx.

Client setup
------------
Run curl in cron.
URL format:
```
/feed/<email>/<client string>/<watchdog time in seconds>
```

So for example, if you used the following url, you'd receive emails at
`mike@example.com` whenever the server called `diamond` failed to respond for
`1800` seconds (aka 30 minutes).

```
curl http://server:14567/feed/mike@example.com/diamond/1800
```

Misc
----
The first time a client hits a URL, feedable will remember the settings. If you
restart feedable, all settings will be lost. Feedable will send one email when a
client misses check-in, then one email if and when the client reconnects.

Feedable relies on a working MTA setup on the server. It doesn't contain any
logic for sending emails itself.

Feedable will dump the state of all of its clients if you visit:
```
curl http://server:14567/feed/state
```

Make sure to protect this with Basic auth or a firewall, as it can be used to
send emails to arbitrary addresses.

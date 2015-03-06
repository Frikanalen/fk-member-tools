# fk-member-tools

Tools for members to talk to the web API and control pages of the
Norwegian open channel Frikanalen.  The latest version of this source
can be found at <URL: https://github.com/Frikanalen/fk-member-tools >.

If you got a TED talk you want to schedule, you can add it to Frikanalen like this:

  echo https://archive.org/details/BenWellington_2014X > ted.txt
  ./bin/process-ted-wishlist ted.txt

When you know the ID of the uploaded video, it can be scheduled for
broadcasting.  This is a good way to add an entry to the schedule:

  PYTHONPATH=. ./bin/schedule 623885 2016-01-01T04:00:00

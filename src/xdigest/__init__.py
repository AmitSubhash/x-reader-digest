"""x-reader-digest: turn your X reposts into a readable email digest.

Pipeline stages:
    capture   -> pull recent reposts (twscrape)
    extract   -> resolve links, classify, pull article text or video transcript
    summarize -> claude -p (sonnet) writes summaries and watch/read verdicts
    render    -> build the email body
    draft     -> create a Gmail draft to yourself
"""

__version__ = "0.1.0"

import twitter

class EmailStatus:
    pass

class TweetStatus():
    def __init__(self, auth):
        self.api = twitter.Api(consumer_key=auth['consumer_key'],
                               consumer_secret=auth['consumer_secret'],
                               access_token_key=auth['access_token_key'],
                               access_token_secret=auth['access_token_secret'])

    def send(self, msg):
        return self.api.PostUpdate(msg)

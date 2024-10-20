## Firestore TSDB Extension

### Configurations

You can config this extension by providing following environments:

- credentials: a dict, represents the contents of certificate, which is from Google service account
- collection_name: a string, denotes the collection to store chat contents
- channel_name: a string, used to fetch the corresponding document in storage
- In addition, to implement the deletion of document based on ttl (which is 1 day by default, and will refresh each time fetching the document), you should set TTL or define Cloud Functions with Firestoe

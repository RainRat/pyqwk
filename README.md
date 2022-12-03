# pyqwk
 .qwk reader in python


For data archivists that want to archive .QWK mail archives in a more readable format. It was popular back in the Fidonet and BBS days, and people may want to archive them now.

Exports the entire messages.dat to a more readable format without setting up a .QWK reader, which might not even have a function to export the entire file.

.QWK archives are a ZIP file, which contains the messages in messages.dat, plus some index files. This program can take either the messages.dat or the .qwk file:

messages.dat: The indexes aren't needed, the only downside is that it doesn't have the names of the subboards the messages are from.

.qwk file: It will use the CONTROL.DAT to retrieve the names of the conferences.

Known issue: Some .qwk packets from this era use a ZIP compression method that modern Python doesn't know.
  
Workaround 1: Some archive utilities have an tool to repack archives into modern formats. Some even have a method to do it in bulk.

Workaround 2: Unpack the archive and act on messages.dat

For each message, the headers aren't exported in the same order they appear in messages.dat; I rearrange them to an order that might make more sense to a modern reader.

It'll leave out message ids, which probably aren't useful to a modern reader, but use --verbose if you want them.

It'll leave out messages marked as private. If you are an archivist, you could leave that as is, to not include personal messages from people kind enough to donate their QWK packets. But if you're archiving your own, use --private to include them.

Apparently there's a password protection option for messages. I've never heard of that until now. They'll be skipped.

This was late night coding binge. probably has bugs. will accept pull requests.
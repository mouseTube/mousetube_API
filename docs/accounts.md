# Account requests

1. The user registers with an **institutional** e-mail address (personal providers such as Gmail are refused).
2. The account is created **inactive** and the user receives a link to confirm the address.
3. Once the link is opened, `DEFAULT_ADMIN_EMAIL` receives a message with a link to the account in the admin. Opening the link twice does not send a second message.
4. In the admin, **Users**, the filter *Account request* gives two lists: *To review (e-mail confirmed)* and *Waiting for e-mail confirmation*. The link in the e-mail to the admin opens the first one. For each request the admin can:
   - tick **Active** on the account and save, or select several and run **Activate selected accounts** (refused if the e-mail is not confirmed);
   - select them and run **Reject selected requests**: a page asks for an optional reason, then the request is deleted and the person is told by e-mail. Only inactive accounts that never logged in can be rejected; if the e-mail cannot be sent, the request is kept.
5. The user receives an e-mail saying the account is active (or the refusal, with the reason).

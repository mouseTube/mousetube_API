# Account requests

1. The user registers with an **institutional** e-mail address (personal providers such as Gmail are refused).
2. The account is created **inactive** and the user receives a link to confirm the address.
3. Once the link is opened, `DEFAULT_ADMIN_EMAIL` receives a message with a link to the account in the admin. Opening the link twice does not send a second message.
4. In the admin, **Users**, the filter *Account request* gives two lists: *To review (e-mail confirmed)* and *Waiting for e-mail confirmation*. The link in the e-mail to the admin opens the first one. For each request the admin can:
   - tick **Active** on the account and save, or select several and run **Activate selected accounts** (refused if the e-mail is not confirmed);
   - select them and run **Reject selected requests**: a page asks for an optional reason, then the request is deleted and the person is told by e-mail. Only inactive accounts that never logged in can be rejected; if the e-mail cannot be sent, the request is kept.
5. The user receives an e-mail saying the account is active (or the refusal, with the reason).

## Registering with ORCID

The form can be started from ORCID. ORCID only gives what is public on the record of the person: the first and last name fill the form, and so does an institutional address if one is public (a personal one is not offered, it would be refused). A name or an address that is private is left to type, and the form says so. The address is confirmed by the link that is sent to it, like any other: it is never taken as verified because ORCID gave it.

## Changing a password

- **Signed in:** `POST /auth/users/set_password/` with `current_password`, `new_password` and `re_new_password`
  (page *My account*, tab *Preferences*, section *Password*). The current password is asked, so a stolen session is not
  enough, and it needs no e-mail. The new password goes through the same validators as the registration. The
  attempts are limited like the login (10 a minute per address), because the current password could be guessed
  there. The API does not compare `re_new_password` with `new_password`: the form of the site does.
- **Forgotten:** `POST /auth/users/reset_password/` sends a link by e-mail (also limited), which opens
  `password/reset/confirm/<uid>/<token>` on the site.
- A new password ends the sign-ins made with the old one (see below): the page signs in again for the user.

## Log out of all devices

`POST /auth/logout_all/` (signed in) ends **every** sign-in of the user made up to now, the one that asks included; other
users are not touched. A JWT cannot be taken back once it is issued, so the server remembers, by user, the moment up to
which the sign-ins are revoked (`UserProfile.sessions_revoked_at`) and refuses an access or a refresh token made for a
sign-in up to then (**401**, `session_revoked`; the renewal at `/auth/jwt/refresh/` too). A token carries the moment of
its sign-in in milliseconds (`iat_ms`): the standard `iat` is in seconds, too coarse to sign in again right after the
revocation. A token made before this existed has no `iat_ms` and is read with its `iat`.

- It is also done when a **password changes**, whoever changes it (the user, the e-mail of a forgotten one, an
  administrator): every `save()` of a user with a new password. A bulk `update()` does not go through it.
- A sign-in only updates the last login: it does not end the other sign-ins of the user, so a phone and a laptop live
  together until one of them asks.
- Nothing is written for a user who never revoked: the field is empty and the check costs one query by call.

## Deleting an account

A user asks by e-mail to `mousetube@igbmc.fr` (the section *Delete my account* of the page *My account* writes it).
The right to erasure of the GDPR asks for an answer **within one month**.

1. **Check who writes:** the e-mail must come from the address of the account. Otherwise ask for a confirmation from it.
2. **Delete the account** in the admin, *Users*: tick it, then *Delete selected users*. Do not delete the last
   administrator.
3. **What stays:** the profile is deleted with the account. The sessions, files and entries that the user created are
   kept, with `created_by` emptied: they stay, no longer linked to the person. Names typed as text (a contact, an
   author in a description) are not linked to the account and stay; remove them by hand if the person asks.
4. **What is not ours:** a record already published on Zenodo stays public there, under its own rules.
5. **Answer** to the person, and keep a note of the request and of the date (to show the delay was met).

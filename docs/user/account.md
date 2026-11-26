# Your account

Open the person icon in the top bar to reach your account.

<figure markdown>
  ![The account page: profile with name, laboratory and ORCID, and the tabs Preferences, My vocalizations, My hardware, My software and API token](../assets/img/account.png)
  <figcaption>Your account, with the number of your own items on each tab.</figcaption>
</figure>

| Tab | What it is for |
|---|---|
| **Profile** | Your name, your laboratory (choose one, or create it) and your ORCID. **Link my ORCID** connects your ORCID iD. |
| **Preferences** | Show your e-mail next to your recordings (off by default), and the display of the lists (cards or table). |
| **My vocalizations** | Your sessions by state, with the actions that suit each one. See [Share and validation](share.md). |
| **My hardware**, **My software** | The equipment and software you created, with their state (draft, waiting, validated). |
| **API token** | A personal key for scripts. See below. |

## Change your password

On your account page, in the **Preferences** tab, the **Password** section changes it: type your **current password**, then
the new one twice. The new password follows the rules of the registration form: at least 8 characters, not only digits,
not a common password. It does not need an e-mail. If you **forgot** it, use *Forgot your password?* on the sign-in
page: you receive a link by e-mail.

## Favorites

Mark protocols, hardware, software, animal profiles, strains, laboratories, references or contacts as
**favorites**: they come first in the lists you pick from. Favorites are personal.

## The API token

The **API token** tab gives a personal **access token**: it lets a program act as **you** on the mouseTube API.
It is for developers; see the [REST API](../dev/api/index.md).

!!! danger "Keep it secret"
    Anyone who has your token can act on your behalf. Never put it in code others can read. It stops working
    after an hour, and you can get a new one.

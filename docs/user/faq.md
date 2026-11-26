# FAQ and glossary

## Questions

??? question "Do I need an account to download recordings?"
    Not to download a file: browsing, searching and downloading a file (or any file of its Zenodo record, one by
    one) are open to everybody. You need an account to download a **whole record or a whole dataset in one zip**,
    and to add data.

??? question "How do I download a whole dataset?"
    Sign in, open the page **Dataset** and use the download button of the dataset: choose **Sound files only**
    (the recordings) or **All files** (with the images and the analyses). To get every file of one record, unfold
    a file and use **Download all (zip)**. A very large dataset is refused: download its files one by one.

??? question "Can I get a copy of my data?"
    Yes. On your account page, **Preferences** tab, section **My data**, **Download my data** gives a JSON file with your
    profile and everything you added.

??? question "How do I change my e-mail address?"
    On your account page, **Profile** tab, **Change e-mail**: type the new institutional address and your current
    password. A link is sent to the new address; open it while signed in and the address changes.

??? question "How do I change my password?"
    On your account page, **Preferences** tab, section **Password**: type your current password and the new one twice. If
    you forgot it, use *Forgot your password?* on the sign-in page (a link is sent by e-mail).

??? question "Why can't I register with my Gmail address?"
    mouseTube asks for an **institutional** e-mail address (university, research institute, hospital) because
    an administrator checks that the data come from researchers. Use your work address.

??? question "I confirmed my e-mail but I still cannot sign in."
    An administrator has to activate your account. You are told by e-mail. The login page also tells you where
    your request stands.

??? question "Why is my session not public after I shared it?"
    It uses something nobody validated yet, so it **waits for validation** and stays private. The Visibility card
    lists what is waiting. See [Share and validation](share.md).

??? question "I cannot edit my session."
    A session **waiting for validation** is locked while an administrator reads it. **Withdraw** it from
    *My vocalizations*, edit it, then share it again. A shared or published session is not locked.

??? question "I cannot change a laboratory, a strain or a piece of equipment I created."
    Once an administrator **validated** it, it is shared by everybody and locked. Ask an administrator to
    correct it.

??? question "A microphone I added is not shown on my public session."
    It is not validated yet: it is hidden from the others (you still see it) until an administrator validates
    it.

??? question "Where are the audio files stored?"
    In a **repository**, most often Zenodo. mouseTube keeps the description and the links. Use the Download
    button or the DOI.

??? question "Can I put my files somewhere else and just describe them on mouseTube?"
    Yes. Give the **download link** and the **DOI** of the file when you add it: mouseTube records them without
    depositing anything.

??? question "How do I cite my data?"
    Publish the session to get a **DOI**, then cite it like any dataset. See [Publish with a DOI](publish.md).

??? question "Can I use mouseTube from a program?"
    Yes, with the REST API. See the [developer documentation](../dev/api/index.md).

## Glossary

<dl>
<dt>Animal profile</dt><dd>The kind of animals recorded: strain, sex, age, genotype, treatment and diet.</dd>
<dt>Controlled vocabulary / ontology</dt><dd>A reference list of terms with an identifier (for example <code>EFO:0000606</code> for the C57BL/6J strain) so that everybody names things the same way. mouseTube checks the terms at their source.</dd>
<dt>Dataset</dt><dd>A curated collection of sessions with its metadata.</dd>
<dt>Draft</dt><dd>Private work in progress, seen only by its author.</dd>
<dt>DOI</dt><dd>Digital Object Identifier: a permanent link to a deposit, to cite.</dd>
<dt>Protocol</dt><dd>How the recording was set up, written as a code built from its fields.</dd>
<dt>Published</dt><dd>Shared and deposited in a repository, with a DOI.</dd>
<dt>Recording session</dt><dd>A set of recordings made under the same experimental conditions.</dd>
<dt>Repository</dt><dd>A service that stores the files and gives them a DOI (Zenodo).</dd>
<dt>Shared</dt><dd>Public, readable by everybody.</dd>
<dt>USV</dt><dd>Ultrasonic vocalization: a call above the range of human hearing, emitted by rodents.</dd>
<dt>Validated</dt><dd>Checked by a mouseTube administrator. Only validated entries are shown to everybody.</dd>
<dt>Waiting validation</dt><dd>Sent for review: private and locked until an administrator decides.</dd>
</dl>

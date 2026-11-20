"""What a user may do with a recording session: the one place that says it.

The views, the serializer and the website ask this module (the website reads the answer in the
`rights` of a session) instead of each repeating which status allows what:

- the author edits a draft, a shared and a published session (the last two stay public; what
  nobody validated yet is not shown to the others, see `moderation.public_session_data`)
- while an administrator reviews a session ("waiting validation") its author cannot change it, he
  can only withdraw it
- only a draft is deleted or shared by its author; an administrator does anything
"""

from mousetube_api.utils.moderation import DRAFT, WAITING

LOCKED_REASON = (
    "This recording session waits for an administrator's review, so it cannot be changed "
    'meanwhile: withdraw it from the list of "My vocalizations" to edit it.'
)


def session_rights(session, user):
    """The actions `user` may do with `session`, as booleans, with the reason it is locked."""
    staff = bool(user and user.is_authenticated and user.is_staff)
    owner = bool(user and user.is_authenticated and session.created_by_id == user.id)
    waiting = session.status == WAITING
    return {
        "can_edit": staff or (owner and not waiting),
        "can_withdraw": (staff or owner) and waiting,
        "can_share": (staff or owner) and session.status == DRAFT,
        "can_delete": staff or (owner and session.status == DRAFT),
        "locked_reason": LOCKED_REASON if owner and not staff and waiting else "",
    }

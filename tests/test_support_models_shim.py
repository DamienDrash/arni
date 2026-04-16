from app.core.models import (
    ChatMessage,
    ChatSession,
    ContactConsent,
    MemberCustomColumn,
    MemberFeedback,
    MemberImportLog,
    MemberSegment,
    ScheduledFollowUp,
    StudioMember,
)
from app.domains.support.models import (
    ChatMessage as DomainChatMessage,
    ChatSession as DomainChatSession,
    ContactConsent as DomainContactConsent,
    MemberCustomColumn as DomainMemberCustomColumn,
    MemberFeedback as DomainMemberFeedback,
    MemberImportLog as DomainMemberImportLog,
    MemberSegment as DomainMemberSegment,
    ScheduledFollowUp as DomainScheduledFollowUp,
    StudioMember as DomainStudioMember,
)


def test_core_models_reexports_support_domain_models() -> None:
    assert ChatSession is DomainChatSession
    assert ChatMessage is DomainChatMessage
    assert StudioMember is DomainStudioMember
    assert MemberCustomColumn is DomainMemberCustomColumn
    assert MemberImportLog is DomainMemberImportLog
    assert MemberSegment is DomainMemberSegment
    assert ScheduledFollowUp is DomainScheduledFollowUp
    assert MemberFeedback is DomainMemberFeedback
    assert ContactConsent is DomainContactConsent


def test_support_models_keep_legacy_table_names() -> None:
    assert ChatSession.__tablename__ == "chat_sessions"
    assert ChatMessage.__tablename__ == "chat_messages"
    assert StudioMember.__tablename__ == "studio_members"
    assert MemberCustomColumn.__tablename__ == "member_custom_columns"
    assert MemberImportLog.__tablename__ == "member_import_logs"
    assert MemberSegment.__tablename__ == "member_segments"
    assert ScheduledFollowUp.__tablename__ == "scheduled_follow_ups"
    assert MemberFeedback.__tablename__ == "member_feedback"
    assert ContactConsent.__tablename__ == "contact_consents"

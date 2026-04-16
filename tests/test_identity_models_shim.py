from app.core.models import AuditLog, PendingInvitation, RefreshToken, Tenant, UserAccount, UserSession
from app.domains.identity.models import (
    AuditLog as DomainAuditLog,
    PendingInvitation as DomainPendingInvitation,
    RefreshToken as DomainRefreshToken,
    Tenant as DomainTenant,
    UserAccount as DomainUserAccount,
    UserSession as DomainUserSession,
)


def test_core_models_reexports_identity_domain_models() -> None:
    assert Tenant is DomainTenant
    assert UserAccount is DomainUserAccount
    assert AuditLog is DomainAuditLog
    assert PendingInvitation is DomainPendingInvitation
    assert RefreshToken is DomainRefreshToken
    assert UserSession is DomainUserSession


def test_identity_models_keep_legacy_table_names() -> None:
    assert Tenant.__tablename__ == "tenants"
    assert UserAccount.__tablename__ == "users"
    assert AuditLog.__tablename__ == "audit_logs"
    assert PendingInvitation.__tablename__ == "pending_invitations"
    assert RefreshToken.__tablename__ == "refresh_tokens"
    assert UserSession.__tablename__ == "user_sessions"

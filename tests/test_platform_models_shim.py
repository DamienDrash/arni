from app.core.models import Setting, TenantConfig
from app.domains.platform.models import Setting as DomainSetting, TenantConfig as DomainTenantConfig


def test_core_models_reexports_platform_domain_models() -> None:
    assert Setting is DomainSetting
    assert TenantConfig is DomainTenantConfig


def test_platform_models_keep_legacy_table_names() -> None:
    assert Setting.__tablename__ == "settings"
    assert TenantConfig.__tablename__ == "tenant_configs"

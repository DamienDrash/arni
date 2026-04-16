from app.core.models import (
    AddonDefinition,
    ImageCreditBalance,
    ImageCreditPack,
    ImageCreditPurchase,
    ImageCreditTransaction,
    LLMModelCost,
    LLMUsageLog,
    Plan,
    Subscription,
    TenantAddon,
    TokenPurchase,
    UsageRecord,
)
from app.domains.billing.models import (
    AddonDefinition as DomainAddonDefinition,
    ImageCreditBalance as DomainImageCreditBalance,
    ImageCreditPack as DomainImageCreditPack,
    ImageCreditPurchase as DomainImageCreditPurchase,
    ImageCreditTransaction as DomainImageCreditTransaction,
    LLMModelCost as DomainLLMModelCost,
    LLMUsageLog as DomainLLMUsageLog,
    Plan as DomainPlan,
    Subscription as DomainSubscription,
    TenantAddon as DomainTenantAddon,
    TokenPurchase as DomainTokenPurchase,
    UsageRecord as DomainUsageRecord,
)


def test_core_models_reexports_billing_domain_models() -> None:
    assert Plan is DomainPlan
    assert AddonDefinition is DomainAddonDefinition
    assert TenantAddon is DomainTenantAddon
    assert Subscription is DomainSubscription
    assert UsageRecord is DomainUsageRecord
    assert TokenPurchase is DomainTokenPurchase
    assert ImageCreditPack is DomainImageCreditPack
    assert ImageCreditBalance is DomainImageCreditBalance
    assert ImageCreditTransaction is DomainImageCreditTransaction
    assert ImageCreditPurchase is DomainImageCreditPurchase
    assert LLMModelCost is DomainLLMModelCost
    assert LLMUsageLog is DomainLLMUsageLog


def test_billing_models_keep_legacy_table_names() -> None:
    assert Plan.__tablename__ == "plans"
    assert AddonDefinition.__tablename__ == "addon_definitions"
    assert TenantAddon.__tablename__ == "tenant_addons"
    assert Subscription.__tablename__ == "subscriptions"
    assert UsageRecord.__tablename__ == "usage_records"
    assert TokenPurchase.__tablename__ == "token_purchases"
    assert ImageCreditPack.__tablename__ == "image_credit_packs"
    assert ImageCreditBalance.__tablename__ == "image_credit_balances"
    assert ImageCreditTransaction.__tablename__ == "image_credit_transactions"
    assert ImageCreditPurchase.__tablename__ == "image_credit_purchases"
    assert LLMModelCost.__tablename__ == "llm_model_costs"
    assert LLMUsageLog.__tablename__ == "llm_usage_log"

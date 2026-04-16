from app.core.models import Campaign, CampaignOffer, CampaignRecipient, CampaignTemplate, CampaignVariant
from app.domains.campaigns.models import (
    Campaign as DomainCampaign,
    CampaignOffer as DomainCampaignOffer,
    CampaignRecipient as DomainCampaignRecipient,
    CampaignTemplate as DomainCampaignTemplate,
    CampaignVariant as DomainCampaignVariant,
)


def test_core_models_reexports_campaign_domain_models() -> None:
    assert Campaign is DomainCampaign
    assert CampaignTemplate is DomainCampaignTemplate
    assert CampaignVariant is DomainCampaignVariant
    assert CampaignRecipient is DomainCampaignRecipient
    assert CampaignOffer is DomainCampaignOffer


def test_campaign_models_keep_legacy_table_names() -> None:
    assert Campaign.__tablename__ == "campaigns"
    assert CampaignTemplate.__tablename__ == "campaign_templates"
    assert CampaignVariant.__tablename__ == "campaign_variants"
    assert CampaignRecipient.__tablename__ == "campaign_recipients"
    assert CampaignOffer.__tablename__ == "campaign_offers"

"""Database schema constraint, foreign key, and migration round-trip tests."""

from decimal import Decimal
import pytest
from alembic import command
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Dataset,
    DatasetSourceType,
    EvidenceDimension,
    EvidenceDirection,
    EvidenceRecord,
    EvidenceSource,
    ExtractedIndicator,
    ExtractionMethod,
    IndicatorType,
    Investigation,
    InvestigationStatus,
    Marketplace,
    PipelineRun,
    PipelineRunStatus,
    Post,
    ScoringConfig,
    ThreatActor,
    User,
    UserRole,
)


def _create_user(db_session, username="analyst_1", email="analyst_1@example.com") -> User:
    """Helper to create and persist a test user."""
    user = User(
        email=email,
        username=username,
        password_hash="pbkdf2_sha256$test_hash",
        full_name="Forensic Analyst",
        role=UserRole.INVESTIGATOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _create_marketplace(db_session, name="AlphaMarket") -> Marketplace:
    """Helper to create and persist a test marketplace."""
    mkt = Marketplace(name=name, description="Test marketplace", is_fictional=True)
    db_session.add(mkt)
    db_session.flush()
    return mkt


def _create_dataset(db_session, name="Dataset_Alpha") -> Dataset:
    """Helper to create and persist a test dataset."""
    ds = Dataset(name=name, source_type=DatasetSourceType.SAMPLE, is_fictional=True)
    db_session.add(ds)
    db_session.flush()
    return ds


# 1. Unique (marketplace, normalised_username) is enforced
def test_unique_marketplace_username(db_session):
    mkt = _create_marketplace(db_session, name="Market_UniqueTest")
    actor1 = ThreatActor(marketplace=mkt, username="DreadPirate", normalised_username="dreadpirate")
    db_session.add(actor1)
    db_session.flush()

    actor2 = ThreatActor(marketplace=mkt, username="dreadpirate", normalised_username="dreadpirate")
    db_session.add(actor2)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 2. Duplicate post dedupe_hash in the same dataset is rejected
def test_duplicate_post_dedupe_hash_in_same_dataset(db_session):
    mkt = _create_marketplace(db_session, name="Market_PostTest")
    ds = _create_dataset(db_session, name="Dataset_PostTest")
    dedupe_hash = "a" * 64

    post1 = Post(
        dataset=ds,
        marketplace=mkt,
        author_username="vendor_bob",
        content="First listing content",
        dedupe_hash=dedupe_hash,
    )
    db_session.add(post1)
    db_session.flush()

    post2 = Post(
        dataset=ds,
        marketplace=mkt,
        author_username="vendor_bob",
        content="Duplicate listing content",
        dedupe_hash=dedupe_hash,
    )
    db_session.add(post2)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 3. An indicator without a post_id is rejected
def test_indicator_without_post_id_rejected(db_session):
    indicator = ExtractedIndicator(
        post_id=None,
        indicator_type=IndicatorType.WALLET_BTC,
        raw_value="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        normalised_value="1a1zp1ep5qgefi2dmptftl5slmv7divfna",
        extraction_method=ExtractionMethod.REGEX,
        extractor_version="1.0.0",
        is_valid_format=True,
    )
    db_session.add(indicator)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 4. Duplicate (post, type, normalised value) is rejected
def test_duplicate_indicator_rejected(db_session):
    mkt = _create_marketplace(db_session, name="Market_IndicatorTest")
    ds = _create_dataset(db_session, name="Dataset_IndicatorTest")
    post = Post(
        dataset=ds,
        marketplace=mkt,
        author_username="vendor_alice",
        content="Contact me via PGP",
        dedupe_hash="b" * 64,
    )
    db_session.add(post)
    db_session.flush()

    ind1 = ExtractedIndicator(
        post_id=post.id,
        indicator_type=IndicatorType.WALLET_BTC,
        raw_value="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
        normalised_value="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
        extraction_method=ExtractionMethod.REGEX,
        extractor_version="1.0.0",
        is_valid_format=True,
    )
    db_session.add(ind1)
    db_session.flush()

    ind2 = ExtractedIndicator(
        post_id=post.id,
        indicator_type=IndicatorType.WALLET_BTC,
        raw_value="BC1QAR0SRRR7XFKVY5L643LYDNW9RE59GTZZWF5MDQ",
        normalised_value="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
        extraction_method=ExtractionMethod.STRUCTURED_FIELD,
        extractor_version="1.0.0",
        is_valid_format=True,
    )
    db_session.add(ind2)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 5. Evidence with actor_a_id >= actor_b_id is rejected
def test_evidence_actor_order_constraint(db_session):
    mkt = _create_marketplace(db_session, name="Market_EvidenceTest")
    actor1 = ThreatActor(marketplace=mkt, username="ActorOne", normalised_username="actorone")
    actor2 = ThreatActor(marketplace=mkt, username="ActorTwo", normalised_username="actortwo")
    db_session.add_all([actor1, actor2])
    user = _create_user(db_session, username="inv_user1", email="inv_user1@example.com")
    investigation = Investigation(title="Case 101", status=InvestigationStatus.DRAFT, created_by=user.id)
    db_session.add(investigation)
    db_session.flush()

    run = PipelineRun(investigation_id=investigation.id, status=PipelineRunStatus.RUNNING)
    db_session.add(run)
    db_session.flush()

    # Ensure actor_a_id >= actor_b_id triggers check violation
    high_id, low_id = max(actor1.id, actor2.id), min(actor1.id, actor2.id)
    invalid_evidence = EvidenceRecord(
        pipeline_run_id=run.id,
        actor_a_id=high_id,
        actor_b_id=low_id,
        dimension=EvidenceDimension.CRYPTOGRAPHIC,
        evidence_type="shared_bitcoin_wallet",
        direction=EvidenceDirection.SUPPORTING,
        strength=Decimal("0.8500"),
        explanation="Actors shared a Bitcoin wallet",
        details={},
    )
    db_session.add(invalid_evidence)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 6. Strength > 1 is rejected
def test_evidence_strength_check_constraint(db_session):
    mkt = _create_marketplace(db_session, name="Market_StrengthTest")
    actor1 = ThreatActor(marketplace=mkt, username="ActorAlpha", normalised_username="actoralpha")
    actor2 = ThreatActor(marketplace=mkt, username="ActorBeta", normalised_username="actorbeta")
    db_session.add_all([actor1, actor2])
    user = _create_user(db_session, username="inv_user2", email="inv_user2@example.com")
    investigation = Investigation(title="Case 102", status=InvestigationStatus.DRAFT, created_by=user.id)
    db_session.add(investigation)
    db_session.flush()

    run = PipelineRun(investigation_id=investigation.id, status=PipelineRunStatus.RUNNING)
    db_session.add(run)
    db_session.flush()

    low_id, high_id = min(actor1.id, actor2.id), max(actor1.id, actor2.id)
    excessive_evidence = EvidenceRecord(
        pipeline_run_id=run.id,
        actor_a_id=low_id,
        actor_b_id=high_id,
        dimension=EvidenceDimension.STYLOMETRIC,
        evidence_type="cosine_stylometric_similarity",
        direction=EvidenceDirection.SUPPORTING,
        strength=Decimal("1.2500"),  # Invalid: > 1.0
        explanation="Excessive strength score",
        details={},
    )
    db_session.add(excessive_evidence)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 7. Evidence_sources with both post_id and indicator_id null is rejected
def test_evidence_source_has_origin_constraint(db_session):
    mkt = _create_marketplace(db_session, name="Market_SourceTest")
    actor1 = ThreatActor(marketplace=mkt, username="ActorSrc1", normalised_username="actorsrc1")
    actor2 = ThreatActor(marketplace=mkt, username="ActorSrc2", normalised_username="actorsrc2")
    db_session.add_all([actor1, actor2])
    user = _create_user(db_session, username="inv_user3", email="inv_user3@example.com")
    investigation = Investigation(title="Case 103", status=InvestigationStatus.DRAFT, created_by=user.id)
    db_session.add(investigation)
    db_session.flush()

    run = PipelineRun(investigation_id=investigation.id, status=PipelineRunStatus.RUNNING)
    db_session.add(run)
    db_session.flush()

    low_id, high_id = min(actor1.id, actor2.id), max(actor1.id, actor2.id)
    evidence = EvidenceRecord(
        pipeline_run_id=run.id,
        actor_a_id=low_id,
        actor_b_id=high_id,
        dimension=EvidenceDimension.INFRASTRUCTURE,
        evidence_type="shared_server_banner",
        direction=EvidenceDirection.SUPPORTING,
        strength=Decimal("0.7000"),
        explanation="Matching server banner observed",
        details={},
    )
    db_session.add(evidence)
    db_session.flush()

    invalid_source = EvidenceSource(
        evidence_id=evidence.id,
        post_id=None,
        indicator_id=None,
    )
    db_session.add(invalid_source)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 8. Two active scoring configs are rejected
def test_two_active_scoring_configs_rejected(db_session):
    config1 = ScoringConfig(
        name="Default_Baseline",
        version=1,
        weights={"crypto": 0.4, "infra": 0.3, "style": 0.3},
        thresholds={"min_score": 0.65},
        is_active=True,
    )
    db_session.add(config1)
    db_session.flush()

    config2 = ScoringConfig(
        name="Experimental_V2",
        version=1,
        weights={"crypto": 0.5, "infra": 0.2, "style": 0.3},
        thresholds={"min_score": 0.70},
        is_active=True,  # Second active row violates partial index
    )
    db_session.add(config2)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 9. Deleting a post cascades to its indicators
def test_delete_post_cascades_to_indicators(db_session):
    mkt = _create_marketplace(db_session, name="Market_CascadeTest")
    ds = _create_dataset(db_session, name="Dataset_CascadeTest")
    post = Post(
        dataset=ds,
        marketplace=mkt,
        author_username="vendor_cascade",
        content="Contact details enclosed",
        dedupe_hash="c" * 64,
    )
    db_session.add(post)
    db_session.flush()

    indicator = ExtractedIndicator(
        post_id=post.id,
        indicator_type=IndicatorType.DOMAIN,
        raw_value="darkmarketxyz.onion",
        normalised_value="darkmarketxyz.onion",
        extraction_method=ExtractionMethod.REGEX,
        extractor_version="1.0.0",
        is_valid_format=True,
    )
    db_session.add(indicator)
    db_session.flush()
    indicator_id = indicator.id

    # Delete the parent post
    db_session.delete(post)
    db_session.flush()

    # Confirm child indicator was deleted by ON DELETE CASCADE
    remaining = db_session.execute(
        select(ExtractedIndicator).where(ExtractedIndicator.id == indicator_id)
    ).scalar_one_or_none()
    assert remaining is None


# 10. Deleting a user who created an investigation is rejected (RESTRICT)
def test_delete_user_with_investigation_restricted(db_session):
    user = _create_user(db_session, username="lead_agent", email="lead_agent@example.com")
    investigation = Investigation(
        title="Operation Nightshade",
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(investigation)
    db_session.flush()

    # Attempt to delete user while referenced by an investigation
    db_session.delete(user)
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.flush()


# 11. Alembic upgrade head then downgrade base works
def test_alembic_round_trip(alembic_cfg):
    """Confirm schema can be downgraded to base and upgraded back to head cleanly."""
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

from backend.database import SessionLocal, Ad, init_db
import datetime

def test_db():
    print("Initializing DB...")
    init_db()
    db = SessionLocal()
    
    # Try to add a test ad
    print("Adding a test ad...")
    test_ad = Ad(
        external_id="test_id_" + str(datetime.datetime.utcnow().timestamp()),
        platform="Test",
        content="Test Content",
        headline="Test Headline",
        start_date=datetime.datetime.utcnow()
    )
    db.add(test_ad)
    db.commit()
    print("Test ad added.")
    
    # Read all ads
    ads = db.query(Ad).all()
    print(f"Total ads in DB: {len(ads)}")
    for ad in ads:
        print(f"- {ad.platform}: {ad.headline}")
    
    db.close()

if __name__ == "__main__":
    test_db()

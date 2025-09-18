# debug_env_test.py - Create this as a separate file to test Railway environment
import os
import sys
from datetime import datetime

def debug_environment_variables():
    """Debug Railway environment variables directly"""
    print("=" * 60)
    print("RAILWAY ENVIRONMENT VARIABLE DIRECT TEST")
    print("=" * 60)
    print(f"Python Version: {sys.version}")
    print(f"Test Time: {datetime.utcnow().isoformat()}")
    print()
    
    # Test Railway-specific variables
    print("RAILWAY ENVIRONMENT:")
    railway_vars = [k for k in os.environ.keys() if k.startswith('RAILWAY_')]
    for var in railway_vars:
        print(f"  {var}: {os.environ[var]}")
    print()
    
    # Test our critical variables
    print("CRITICAL APPLICATION VARIABLES:")
    critical_vars = [
        'GHL_API_KEY',
        'GHL_LOCATION_ID', 
        'GOOGLE_API_KEY',
        'GOOGLE_CSE_CX',
        'JWT_SECRET'
    ]
    
    for var in critical_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: EXISTS (length: {len(value)}, type: {type(value).__name__})")
            print(f"   Preview: {value[:8]}{'...' + value[-4:] if len(value) > 12 else ''}")
            print(f"   Repr: {repr(value[:20])}")
        else:
            print(f"❌ {var}: MISSING")
            # Check for similar names
            similar = [k for k in os.environ.keys() if var.lower() in k.lower()]
            if similar:
                print(f"   Similar variables found: {similar}")
    
    print()
    print("ALL ENVIRONMENT VARIABLES:")
    all_vars = sorted(os.environ.keys())
    for var in all_vars:
        value = os.environ[var]
        if len(value) > 50:
            preview = value[:30] + "..." + value[-10:]
        else:
            preview = value
        print(f"  {var}: {preview}")
    
    print()
    print(f"Total environment variables: {len(os.environ)}")
    print("=" * 60)

if __name__ == "__main__":
    debug_environment_variables()

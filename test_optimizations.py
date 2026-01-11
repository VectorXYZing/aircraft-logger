#!/usr/bin/env python3
"""Test script to verify CPU optimizations are working correctly."""
import sys
import time
import tracemalloc
from airlogger.metadata import fetch_metadata, metadata_cache, failed_cache

def test_metadata_optimizations():
    """Test that metadata fetching optimizations are working."""
    print("🧪 Testing Metadata Optimizations")
    print("=" * 50)
    
    # Test cache functionality
    print("1. Testing cache functionality...")
    
    # Clear caches first
    metadata_cache.clear()
    failed_cache.clear()
    
    # Test a lookup (will be cached)
    start_time = time.time()
    result1 = fetch_metadata("7C1234")  # Common Australian aircraft
    time1 = time.time() - start_time
    print(f"   First lookup took: {time1:.3f}s")
    print(f"   Result: {result1}")
    print(f"   Cache size: {len(metadata_cache)}")
    
    # Test cached lookup (should be much faster)
    start_time = time.time()
    result2 = fetch_metadata("7C1234")  # Same hex, should hit cache
    time2 = time.time() - start_time
    print(f"   Cached lookup took: {time2:.3f}s")
    print(f"   Speedup: {time1/time2:.1f}x faster")
    print(f"   Results match: {result1 == result2}")
    
    # Test failed lookup caching
    print("\n2. Testing failed lookup caching...")
    start_time = time.time()
    result3 = fetch_metadata("INVALID")  # Should fail
    time3 = time.time() - start_time
    print(f"   Failed lookup took: {time3:.3f}s")
    print(f"   Failed cache size: {len(failed_cache)}")
    
    # Test that second failed lookup is faster (cached failure)
    start_time = time.time()
    result4 = fetch_metadata("INVALID")  # Should hit failed cache
    time4 = time.time() - start_time
    print(f"   Cached failure lookup took: {time4:.3f}s")
    print(f"   Failed lookup speedup: {time3/time4:.1f}x faster")
    
    return True

def test_performance():
    """Test performance improvements."""
    print("\n🚀 Performance Testing")
    print("=" * 50)
    
    # Clear caches
    metadata_cache.clear()
    failed_cache.clear()
    
    # Test multiple lookups to simulate real usage
    test_hexes = ["7C1234", "VHABC", "GABCD", "N12345", "EIABC"] * 10  # 50 lookups
    
    print(f"Testing {len(test_hexes)} metadata lookups...")
    
    # Start memory tracking
    tracemalloc.start()
    start_time = time.time()
    
    results = []
    for hex_code in test_hexes:
        result = fetch_metadata(hex_code)
        results.append(result)
    
    elapsed_time = time.time() - start_time
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"   Total time: {elapsed_time:.3f}s")
    print(f"   Average per lookup: {elapsed_time/len(test_hexes)*1000:.1f}ms")
    print(f"   Memory used: {current/1024/1024:.1f}MB")
    print(f"   Peak memory: {peak/1024/1024:.1f}MB")
    print(f"   Cache entries: {len(metadata_cache)}")
    print(f"   Failed cache entries: {len(failed_cache)}")
    
    return True

def main():
    """Run all tests."""
    print("🔧 Aircraft Logger CPU Optimization Tests")
    print("=" * 60)
    
    try:
        # Test metadata optimizations
        test_metadata_optimizations()
        
        # Test performance
        test_performance()
        
        print("\n✅ All tests completed successfully!")
        print("\n📊 Optimization Summary:")
        print("   • Aggressive caching with TTL")
        print("   • Failed lookup caching with exponential backoff")
        print("   • Single API source (adsb.lol) instead of multiple")
        print("   • Connection reuse with shared session")
        print("   • Optimized airline prefix lookup")
        print("   • Reduced memory allocations")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
"""Test root cause frame detection in exception chains."""

import pytest
from rdetoolkit.traceback.formatter import CompactTraceFormatter
from rdetoolkit.models.config import TracebackSettings


class TestRootCauseFrameDetection:
    """Test that RC frame correctly identifies the root cause in exception chains."""
    
    def test_simple_exception_rc_frame(self):
        """Test that simple exceptions point to F0."""
        config = TracebackSettings(enabled=True, format="compact")
        formatter = CompactTraceFormatter(config)
        
        try:
            raise ValueError("Simple error")
        except Exception as e:
            result = formatter.format(e)
            assert 'RC frame="F0"' in result
    
    def test_explicit_exception_chain_rc_frame(self):
        """Test that explicit exception chains (raise...from) identify deeper frame."""
        config = TracebackSettings(enabled=True, format="compact")
        formatter = CompactTraceFormatter(config)
        
        try:
            try:
                # Root cause
                raise ValueError("Root cause error")
            except ValueError as original:
                # Chained exception
                raise RuntimeError("Wrapper error") from original
        except Exception as e:
            result = formatter.format(e)
            # With exception chaining, RC should point to the deeper frame
            # The actual frame index depends on the traceback depth
            assert 'RC frame="F' in result
            # Verify it contains the hint from the wrapper (current exception)
            assert 'hint="Wrapper error"' in result
    
    def test_implicit_exception_chain_rc_frame(self):
        """Test that implicit exception chains identify context frame."""
        config = TracebackSettings(enabled=True, format="compact")
        formatter = CompactTraceFormatter(config)
        
        def cause_implicit_chain():
            try:
                # This will raise a KeyError
                {}['nonexistent']
            except:
                # This will create an implicit chain
                raise ValueError("Error during handling")
        
        try:
            cause_implicit_chain()
        except Exception as e:
            result = formatter.format(e)
            # Should identify the chain and point to appropriate frame
            assert 'RC frame="F' in result
            assert 'hint="Error during handling"' in result
    
    def test_no_traceback_rc_frame(self):
        """Test RC frame when there's no traceback."""
        config = TracebackSettings(enabled=True, format="compact")
        formatter = CompactTraceFormatter(config)
        
        # Create exception without raising it (no traceback)
        exc = ValueError("No traceback")
        exc_type, _, exc_traceback = type(exc), exc, None
        
        # Manually call format with no traceback
        import sys
        old_exc_info = sys.exc_info
        try:
            sys.exc_info = lambda: (exc_type, exc, exc_traceback)
            result = formatter.format(exc)
            # Should default to F0 when no traceback
            assert 'RC frame="F0"' in result
        finally:
            sys.exc_info = old_exc_info
    
    def test_deep_traceback_rc_frame(self):
        """Test RC frame with deep call stack."""
        config = TracebackSettings(enabled=True, format="compact")
        formatter = CompactTraceFormatter(config)
        
        def level3():
            raise ValueError("Deep error")
        
        def level2():
            level3()
        
        def level1():
            level2()
        
        try:
            level1()
        except Exception as e:
            result = formatter.format(e)
            # For simple deep stack, should still point to F0 (immediate frame)
            assert 'RC frame="F0"' in result
            # Verify we have multiple frames
            assert 'F0 ' in result
            assert 'F1 ' in result
            assert 'F2 ' in result
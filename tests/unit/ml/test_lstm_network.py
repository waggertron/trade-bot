"""Tests for LSTMNetwork PyTorch module."""

from __future__ import annotations

import pytest


class TestLSTMNetworkForwardPass:
    def test_output_shape_batch_4(self):
        """Forward pass with batch_size=4 produces (4, 3) output."""
        torch = pytest.importorskip("torch")
        from src.ml.lstm_network import LSTMNetwork

        net = LSTMNetwork(input_size=10, hidden_size=32, num_layers=2, num_classes=3)
        x = torch.randn(4, 20, 10)  # (batch=4, seq_len=20, features=10)
        out = net(x)
        assert out.shape == (4, 3)

    def test_output_has_three_classes(self):
        """Output dimension matches num_classes=3."""
        torch = pytest.importorskip("torch")
        from src.ml.lstm_network import LSTMNetwork

        net = LSTMNetwork(input_size=5, num_classes=3)
        x = torch.randn(2, 10, 5)
        out = net(x)
        assert out.shape[1] == 3

    def test_batch_size_one(self):
        """Handles batch_size=1 without error."""
        torch = pytest.importorskip("torch")
        from src.ml.lstm_network import LSTMNetwork

        net = LSTMNetwork(input_size=8, hidden_size=16, num_layers=1)
        x = torch.randn(1, 5, 8)
        out = net(x)
        assert out.shape == (1, 3)

    def test_different_sequence_lengths(self):
        """Different sequence lengths produce the same output feature dimension."""
        torch = pytest.importorskip("torch")
        from src.ml.lstm_network import LSTMNetwork

        net = LSTMNetwork(input_size=6, hidden_size=32, num_layers=2)

        x_short = torch.randn(2, 5, 6)
        x_long = torch.randn(2, 50, 6)

        out_short = net(x_short)
        out_long = net(x_long)

        assert out_short.shape == (2, 3)
        assert out_long.shape == (2, 3)

    def test_custom_num_classes(self):
        """Output dimension matches a custom num_classes value."""
        torch = pytest.importorskip("torch")
        from src.ml.lstm_network import LSTMNetwork

        net = LSTMNetwork(input_size=4, num_classes=5)
        x = torch.randn(3, 10, 4)
        out = net(x)
        assert out.shape == (3, 5)

    def test_single_layer_no_dropout_error(self):
        """Single layer LSTM with dropout param should not raise (dropout is ignored)."""
        torch = pytest.importorskip("torch")
        from src.ml.lstm_network import LSTMNetwork

        net = LSTMNetwork(input_size=4, num_layers=1, dropout=0.5)
        x = torch.randn(2, 10, 4)
        out = net(x)
        assert out.shape == (2, 3)

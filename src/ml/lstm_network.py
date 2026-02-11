"""PyTorch LSTM network for sequential prediction."""

from __future__ import annotations

try:
    import torch
    import torch.nn as nn

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


if HAS_TORCH:

    class LSTMNetwork(nn.Module):
        """Multi-layer LSTM followed by a fully connected classifier."""

        def __init__(
            self,
            input_size: int,
            hidden_size: int = 64,
            num_layers: int = 2,
            num_classes: int = 3,
            dropout: float = 0.2,
        ) -> None:
            super().__init__()
            self.lstm = nn.LSTM(
                input_size,
                hidden_size,
                num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0.0,
            )
            self.fc = nn.Linear(hidden_size, num_classes)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            """Run forward pass.

            Args:
                x: Input tensor of shape (batch_size, sequence_length, input_size).

            Returns:
                Logits tensor of shape (batch_size, num_classes).
            """
            # x shape: (batch_size, sequence_length, input_size)
            out, _ = self.lstm(x)
            # Take last time step
            out = out[:, -1, :]
            return self.fc(out)

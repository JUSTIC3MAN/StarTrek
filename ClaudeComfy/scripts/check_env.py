import torch
import comfy_kitchen
import av

print("torch", torch.__version__, "| CUDA", torch.version.cuda, "| GPU available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
print("comfy_kitchen", getattr(comfy_kitchen, "__version__", "?"), "| PyAV", av.__version__)
if not torch.cuda.is_available():
    raise SystemExit("PyTorch cannot see the GPU - check the NVIDIA driver (CUDA 13.0 needs driver 580 or newer).")

[90004] Title: Niko1221/Strata@v0.2.4: README.md lines 140-200 (source code)
URL: https://github.com/Niko1221/Strata/blob/v0.2.4/README.md#L140-L200
[PARTLY OTHER ENGINE: the parts "### Low on memory? Try Gyro" (lines 154-165), "### The other sizes" (lines 166-190) of this page describe Strata's Qwen engine; the task is about its DeepSeek engine - flags, settings and numbers from those parts are not the DeepSeek engine's unless that engine's code shows them; quotes from them are marked [OTHER ENGINE]]

140: ```text
141: Set up Strata on this PC for me: https://github.com/Niko1221/Strata - follow docs/AI_SETUP.md in that repository.
142: ```
143: 
144: It checks your graphics card, RAM and disk, picks the model that fits, installs and starts it, and tells you how to
145: connect your apps. AI tools can also install, start and stop Strata through its [MCP server](docs/MCP_SERVER.md).
146: 
147: Prefer to build it yourself? See [Build from source](#build-from-source).
148: 
149: ## Models
150: 
151: The app and `strata launch` recommend a model for your memory. It is one model in several sizes, compressed more or less.
152: Smaller sizes are faster. Larger sizes are a bit smarter.
153: 
[OTHER ENGINE from here (line 154, part ### Low on memory? Try Gyro): Strata's Qwen engine]
154: ### Low on memory? Try Gyro
155: 
156: [Gyro](https://huggingface.co/agentionai/Qwen3.8-Flash-Next-Gyro-GGUF) (by agentionai) is the smallest way to run this model.
157: 
158: | Size | Memory it needs (RAM + VRAM) | Download | What it is |
159: | --- | ---: | ---: | --- |
160: | **Gyro-S** | 27.6 GB | 58.5 GB | For PCs that fit nothing else. Quality is lower than IQ2_XS. |
161: | **Gyro-M** | 35 GB | 92.0 GB | About IQ3_XXS quality with about 20% less GPU memory. It writes answers 16% (12 GB RTX 3060) to 21% (R9700) slower than Q2_0. |
162: 
163: Gyro runs on NVIDIA and AMD cards (AMD is experimental) on Intel Arc cards on Linux (tested on an Arc A750) and, from 0.2.2, on Apple Silicon Macs (Gyro-S on a 32 GB Mac mini: 9 tok/s, streaming from the SSD; [docs/MAC.md](docs/MAC.md#gyro-
164: [docs/GYRO.md](docs/GYRO.md). Start it with `strata launch --model gyro-s`.
165: 
[OTHER ENGINE from here (line 166, part ### The other sizes): Strata's Qwen engine]
166: ### The other sizes
167: 
168: The tiers count your RAM plus your VRAM, less 5 GB that Windows and the system keep for themselves. Every other size stays a choice.
169: 
170: | Your memory (RAM + VRAM) | Take | Notes |
171: | --- | --- | --- |
172: | **32 GB** | **Gyro-S**, or the **[Coder](docs/MODELS.md#coder)** for code | The Coder needs 32 GB of RAM and keeps half of the experts, so it is weaker outside code |
173: | **40 GB** | **[Swift 1.5](docs/MODELS.md#swift-15)** IQ2_XS (39.2 GB), or **Gyro-M** (35 GB) | Swift thinks for a shorter time before it answers. Gyro-M is close to IQ3_XXS in quality, but it writes answers 16-21% slower than Q2_0 |
174: | **48 GB** | **IQ3_XXS** (47.0 GB) | Slower, better |
175: | **64 GB** | **IQ3_S** (54.8 GB), the original or Swift 1.5 | The slowest, the best: it matches the full model on the published tests |
176: | **96 GB or more** | Unsloth's **UD-IQ4_XS** (about 72 GB of RAM) to **Q8_0** (about 136 GB), 4 to 8 bit | Closer to the full model. With less RAM, Strata reads part of them from the SSD, which is much slower |
177: 
178: Less RAM than a row says can still work: Strata switches to its
179: [low-RAM mode](docs/MODELS.md#a-big-graphics-card-and-little-ram) by itself. Expect it to be slower, and much slower
180: with a small graphics card.
181: 
182: More choices:
183: 
184: - **[Swift 1.5](docs/MODELS.md#swift-15)** is a fine-tune that thinks for a shorter time before it answers, at about the same quality and RAM.
185: - **[NVFP4](docs/NVFP4.md)** is NVIDIA's 4-bit version for NVIDIA cards. It needs about 80 GB of RAM to keep every expert in RAM.
186: - **[Qwen3.6-35B-A3B](docs/QWEN36.md)** is a smaller, different model that reads pictures and can answer several requests at once.
187: - **[OrcaRouter's Uncensored IQ3_XXS](docs/MODELS.md#orcarouter-uncensored-iq3_xxs)** is set up by hand.
188: 
189: Every size, download and what fits where: [docs/MODELS.md](docs/MODELS.md).
190: 
[end of the OTHER ENGINE part]
191: ### DeepSeek V4.1-Flash (in the Terminal, from 0.2.4)
192: 
193: [DeepSeek V4.1-Flash](https://huggingface.co/ISTA-DASLab/DeepSeek-V4.1-Flash-1017-GSQ-RCO-GGUF) is a different, much bigger model. ISTA-DASLab made the three sets below. Strata runs them on a PC with one 12 GB graphics card and 46 to 64 GB 
194: 
195: | Set | Download | Quality against the original model | Writes at |
196: | --- | ---: | --- | --- |
197: | **IQ1_M** (1.75 bits) | 239 GB | KL 0.217, perplexity 3.80 (+21%); code +8.9%, agent work +10.2%; weaker on plain English prose. ISTA-DASLab's model card: keeps 98.7% of the base model's task average (AIME25, GPQA-Diamond, LiveCodeBench v
198: | **IQ2_XXS** (2.00 bits) | 257 GB | KL 0.170, perplexity 3.63 (+15.5%); code +8.6%, agent work +5.3% | 6 to 9 tokens/s on an RTX 3060, about 5 on an RTX 5070 |
199: | **IQ2_XS** (2.25 bits) | 274 GB | KL 0.107, perplexity 3.37 (+7.3%); code +3.2%, agent work +2.2% | about 11 tokens/s on one Radeon AI PRO R9700 |
200: | **IQ4_NL** (Engram table, not a third model) | 111 GB, already in all three downloads above | The 4-bit Engram lookup table the model reads from RAM or SSD. All three sets use this one file (`DeepSeek-V4.1-Flash-Engram-IQ4_NL.gguf`). | n/
(README.md has 414 lines.)

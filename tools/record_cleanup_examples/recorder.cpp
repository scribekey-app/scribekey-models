// Mirrors the Android app's app/src/main/cpp/scribekey_llama.cpp nativeGenerate: same tokenize flags,
// context sizing, greedy sampler (top_k 1, top_p 1, temperature 0, no penalties) and stop markers.
#include "llama.h"
#include <algorithm>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

static int32_t tokenize(const llama_vocab * vocab, const std::string & text, std::vector<llama_token> & tokens) {
    const int32_t max_tokens = std::max<int32_t>(32, static_cast<int32_t>(text.size() * 2 + 8));
    tokens.resize(max_tokens);
    int32_t count = llama_tokenize(vocab, text.data(), (int32_t) text.size(), tokens.data(), max_tokens, false, true);
    if (count < 0) {
        tokens.resize(-count);
        count = llama_tokenize(vocab, text.data(), (int32_t) text.size(), tokens.data(), -count, false, true);
    }
    if (count <= 0) throw std::runtime_error("tokenize failed");
    tokens.resize(count);
    return count;
}

static std::string token_piece(const llama_vocab * vocab, llama_token token) {
    std::vector<char> buffer(256);
    int32_t count = llama_token_to_piece(vocab, token, buffer.data(), buffer.size(), 0, true);
    if (count < 0) {
        buffer.resize(-count);
        count = llama_token_to_piece(vocab, token, buffer.data(), buffer.size(), 0, true);
    }
    return std::string(buffer.data(), count);
}

static bool appended_contains(const std::string & output, size_t previous, std::string_view marker) {
    const size_t overlap = marker.empty() ? 0 : marker.size() - 1;
    const size_t from = previous > overlap ? previous - overlap : 0;
    return output.find(marker.data(), from, marker.size()) != std::string::npos;
}

int main(int argc, char ** argv) {
    if (argc != 5) { std::cerr << "usage: recorder model.gguf prompt.txt context_tokens max_output_tokens\n"; return 2; }
    std::ifstream in(argv[2]);
    std::stringstream buf; buf << in.rdbuf();
    const std::string prompt = buf.str();
    const int context_tokens = std::stoi(argv[3]);
    const int max_output_tokens = std::stoi(argv[4]);

    llama_backend_init();
    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;
    llama_model * model = llama_model_load_from_file(argv[1], mp);
    if (!model) { std::cerr << "load failed\n"; return 1; }
    const llama_vocab * vocab = llama_model_get_vocab(model);
    std::vector<llama_token> prompt_tokens;
    const int32_t prompt_count = tokenize(vocab, prompt, prompt_tokens);

    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = context_tokens; cp.n_batch = context_tokens; cp.n_ubatch = context_tokens; cp.n_seq_max = 1;
    cp.n_threads = 4; cp.n_threads_batch = 4;
    llama_context * ctx = llama_init_from_model(model, cp);
    llama_batch batch = llama_batch_init(std::max(prompt_count, 1), 0, 1);
    for (int32_t i = 0; i < prompt_count; ++i) {
        batch.token[i] = prompt_tokens[i]; batch.pos[i] = i; batch.n_seq_id[i] = 1;
        batch.seq_id[i][0] = 0; batch.logits[i] = i == prompt_count - 1;
    }
    batch.n_tokens = prompt_count;
    if (llama_decode(ctx, batch) != 0) { std::cerr << "decode failed\n"; return 1; }

    llama_sampler * chain = llama_sampler_chain_init(llama_sampler_chain_default_params());
    llama_sampler_chain_add(chain, llama_sampler_init_greedy());

    std::string output;
    for (int generated = 0; generated < max_output_tokens; ++generated) {
        const llama_token token = llama_sampler_sample(chain, ctx, -1);
        if (llama_vocab_is_eog(vocab, token)) break;
        const size_t previous = output.size();
        output += token_piece(vocab, token);
        llama_sampler_accept(chain, token);
        if (appended_contains(output, previous, "<|im_end|>") || appended_contains(output, previous, "<|endoftext|>")) break;
        if (appended_contains(output, previous, "<|im_start|>")) break;
        if (generated + 1 == max_output_tokens) break;
        batch.n_tokens = 1; batch.token[0] = token; batch.pos[0] = prompt_count + generated;
        batch.n_seq_id[0] = 1; batch.seq_id[0][0] = 0; batch.logits[0] = true;
        if (llama_decode(ctx, batch) != 0) { std::cerr << "token decode failed\n"; return 1; }
    }
    std::cout << output;
    llama_sampler_free(chain); llama_batch_free(batch); llama_free(ctx); llama_model_free(model);
    return 0;
}

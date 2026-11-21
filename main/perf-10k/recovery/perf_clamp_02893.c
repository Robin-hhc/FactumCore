/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02893(unsigned int count)
{
    const unsigned int limit = 136u;
    return count > limit ? limit : count;
}

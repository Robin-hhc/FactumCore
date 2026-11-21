/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05424(unsigned int count)
{
    const unsigned int limit = 86u;
    return count > limit ? limit : count;
}

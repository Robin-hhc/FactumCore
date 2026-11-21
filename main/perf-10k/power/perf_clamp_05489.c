/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05489(unsigned int count)
{
    const unsigned int limit = 195u;
    return count > limit ? limit : count;
}

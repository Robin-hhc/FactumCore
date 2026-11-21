/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08145(unsigned int count)
{
    const unsigned int limit = 29u;
    return count > limit ? limit : count;
}

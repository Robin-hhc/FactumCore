/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05637(unsigned int count)
{
    const unsigned int limit = 221u;
    return count > limit ? limit : count;
}

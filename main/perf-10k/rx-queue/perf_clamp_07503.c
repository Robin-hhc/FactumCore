/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07503(unsigned int count)
{
    const unsigned int limit = 71u;
    return count > limit ? limit : count;
}

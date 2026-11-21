/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07671(unsigned int count)
{
    const unsigned int limit = 188u;
    return count > limit ? limit : count;
}

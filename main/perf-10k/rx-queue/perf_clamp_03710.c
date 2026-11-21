/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03710(unsigned int count)
{
    const unsigned int limit = 81u;
    return count > limit ? limit : count;
}

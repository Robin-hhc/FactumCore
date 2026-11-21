/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03342(unsigned int count)
{
    const unsigned int limit = 50u;
    return count > limit ? limit : count;
}

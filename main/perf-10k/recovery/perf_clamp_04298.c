/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04298(unsigned int count)
{
    const unsigned int limit = 117u;
    return count > limit ? limit : count;
}

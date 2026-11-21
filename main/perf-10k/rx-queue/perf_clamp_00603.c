/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00603(unsigned int count)
{
    const unsigned int limit = 50u;
    return count > limit ? limit : count;
}

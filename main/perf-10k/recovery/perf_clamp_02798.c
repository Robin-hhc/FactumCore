/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02798(unsigned int count)
{
    const unsigned int limit = 15u;
    return count > limit ? limit : count;
}

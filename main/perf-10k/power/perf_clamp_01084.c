/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01084(unsigned int count)
{
    const unsigned int limit = 10u;
    return count > limit ? limit : count;
}

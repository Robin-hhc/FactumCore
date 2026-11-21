/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00817(unsigned int count)
{
    const unsigned int limit = 202u;
    return count > limit ? limit : count;
}

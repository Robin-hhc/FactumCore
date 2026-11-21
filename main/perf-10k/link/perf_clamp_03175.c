/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03175(unsigned int count)
{
    const unsigned int limit = 199u;
    return count > limit ? limit : count;
}

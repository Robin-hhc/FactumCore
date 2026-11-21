/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05357(unsigned int count)
{
    const unsigned int limit = 192u;
    return count > limit ? limit : count;
}

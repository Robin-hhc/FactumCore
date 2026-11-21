/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01124(unsigned int count)
{
    const unsigned int limit = 192u;
    return count > limit ? limit : count;
}

/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06104(unsigned int count)
{
    const unsigned int limit = 192u;
    return count > limit ? limit : count;
}

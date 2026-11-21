/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08128(unsigned int count)
{
    const unsigned int limit = 238u;
    return count > limit ? limit : count;
}

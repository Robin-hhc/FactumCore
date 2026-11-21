/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_02572(unsigned int count)
{
    const unsigned int limit = 157u;
    return count > limit ? limit : count;
}

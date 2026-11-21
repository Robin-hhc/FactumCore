/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04930(unsigned int count)
{
    const unsigned int limit = 154u;
    return count > limit ? limit : count;
}

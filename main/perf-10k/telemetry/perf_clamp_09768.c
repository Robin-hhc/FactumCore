/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09768(unsigned int count)
{
    const unsigned int limit = 230u;
    return count > limit ? limit : count;
}

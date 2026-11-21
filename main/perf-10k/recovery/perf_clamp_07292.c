/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_07292(unsigned int count)
{
    const unsigned int limit = 219u;
    return count > limit ? limit : count;
}

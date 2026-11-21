/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_03223(unsigned int count)
{
    const unsigned int limit = 19u;
    return count > limit ? limit : count;
}

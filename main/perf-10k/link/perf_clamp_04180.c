/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04180(unsigned int count)
{
    const unsigned int limit = 103u;
    return count > limit ? limit : count;
}

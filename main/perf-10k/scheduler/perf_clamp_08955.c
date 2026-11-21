/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08955(unsigned int count)
{
    const unsigned int limit = 104u;
    return count > limit ? limit : count;
}

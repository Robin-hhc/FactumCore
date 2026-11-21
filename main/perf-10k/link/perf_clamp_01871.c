/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01871(unsigned int count)
{
    const unsigned int limit = 192u;
    return count > limit ? limit : count;
}

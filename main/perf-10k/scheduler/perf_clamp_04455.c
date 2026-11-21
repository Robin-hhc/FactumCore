/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04455(unsigned int count)
{
    const unsigned int limit = 47u;
    return count > limit ? limit : count;
}
